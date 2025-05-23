package com.statestr.sfp.publication.config;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "jwt.authorization")
public class JwtAuthorizationProperties {
    
    private String authoritiesPrefix = "ROLE_";
    private String groupsClaim = "groups";
    private Map<String, RoleConfig> roles = new HashMap<>();
    
    /**
     * @return the groupsClaim
     */
    public String getGroupsClaim() {
        return groupsClaim;
    }

    /**
     * @param groupsClaim the groupsClaim to set
     */
    public void setGroupsClaim(String groupsClaim) {
        this.groupsClaim = groupsClaim;
    }

    /**
     * @return the authoritiesPrefix
     */
    public String getAuthoritiesPrefix() {
        return authoritiesPrefix;
    }

    /**
     * @param authoritiesPrefix the authoritiesPrefix to set
     */
    public void setAuthoritiesPrefix(String authoritiesPrefix) {
        this.authoritiesPrefix = authoritiesPrefix;
    }

    /**
     * @return the roles
     */
    public Map<String, RoleConfig> getRoles() {
        return roles;
    }

    /**
     * @param roles the roles to set
     */
    public void setRoles(Map<String, RoleConfig> roles) {
        this.roles = roles;
    }
    
    /**
     * 获取组ID到角色的映射
     */
    public Map<String, List<String>> getGroupToAuthorities() {
        Map<String, List<String>> groupToAuthorities = new HashMap<>();
        
        for (Map.Entry<String, RoleConfig> entry : roles.entrySet()) {
            String role = entry.getKey();
            String groupId = entry.getValue().getGroupId();
            
            List<String> authorities = groupToAuthorities.computeIfAbsent(groupId, k -> new ArrayList<>());
            authorities.add(role);
        }
        
        return groupToAuthorities;
    }
    
    /**
     * 获取角色到练习的映射
     */
    public Map<String, List<String>> getGroupToExercises() {
        Map<String, List<String>> groupToExercises = new HashMap<>();
        
        for (Map.Entry<String, RoleConfig> entry : roles.entrySet()) {
            String role = entry.getKey();
            List<String> exercises = entry.getValue().getExercises();
            
            if (exercises != null && !exercises.isEmpty()) {
                groupToExercises.put(role, exercises);
            }
        }
        
        return groupToExercises;
    }
    
    /**
     * 获取允许的角色列表
     */
    public List<String> getAllowedRoles() {
        List<String> allowedRoles = new ArrayList<>();
        
        for (Map.Entry<String, RoleConfig> entry : roles.entrySet()) {
            if (entry.getValue().isAllowed()) {
                allowedRoles.add(entry.getKey());
            }
        }
        
        return allowedRoles;
    }
    
    /**
     * 角色配置类
     */
    public static class RoleConfig {
        private String groupId;
        private boolean allowed = true;
        private List<String> exercises = new ArrayList<>();
        
        public String getGroupId() {
            return groupId;
        }
        
        public void setGroupId(String groupId) {
            this.groupId = groupId;
        }
        
        public boolean isAllowed() {
            return allowed;
        }
        
        public void setAllowed(boolean allowed) {
            this.allowed = allowed;
        }
        
        public List<String> getExercises() {
            return exercises;
        }
        
        public void setExercises(List<String> exercises) {
            this.exercises = exercises;
        }
    }
}
